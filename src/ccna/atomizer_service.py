"""
CCNA Atomizer Service.

AI-powered content generation using Gemini for creating evidence-based learning atoms
from CCNA module content. Implements all 15 learning activity types.

Evidence-Based Principles:
- ATOMICITY: One fact per item (FSRS: S_composite = S_a × S_b / (S_a + S_b))
- OPTIMAL LENGTH: Question 8-15 words, Answer 8-15 (factual) or 15-25 (conceptual) WITH CONTEXT
- RETRIEVAL STRENGTH: Questions require active recall, not recognition
- CONCRETE > ABSTRACT: Specific examples, IPs, commands
- NO HALLUCINATION: Only information explicitly in source content

Hardening:
- Uses json_repair for robust LLM output parsing (handles malformed JSON)
- Tracks parse failures for monitoring silent data loss
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger

# Robust JSON parsing for LLM outputs (handles trailing commas, unescaped quotes, etc.)
try:
    from json_repair import repair_json
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False
    repair_json = None

from config import get_settings
from src.ccna.content_parser import CLICommand, KeyTerm, Section, Table


class AtomType(str, Enum):
    """Learning atom types with effect sizes from research."""

    FLASHCARD = "flashcard"      # d=0.7 - Retrieval
    CLOZE = "cloze"              # d=0.7 - Retrieval, Generation
    MCQ = "mcq"                  # d=0.6 - Discrimination, Retrieval
    TRUE_FALSE = "true_false"   # d=0.5 - Discrimination
    SHORT_ANSWER = "short_answer"  # d=0.7 - Generation, Retrieval
    MATCHING = "matching"        # d=0.6 - Discrimination
    RANKING = "ranking"          # d=0.5 - Discrimination
    SEQUENCE = "sequence"        # d=0.6 - Retrieval
    PARSONS = "parsons"          # d=0.6 - Application (CLI ordering)
    NUMERIC = "numeric"          # d=0.7 - Application (Binary/Hex/Subnetting)
    EXPLAIN = "explain"          # d=0.6 - Elaboration
    COMPARE = "compare"          # d=0.6 - Elaboration
    PROBLEM = "problem"          # d=0.5 - Application
    PREDICTION = "prediction"    # d=0.5 - Elaboration
    PASSAGE_BASED = "passage_based"  # d=0.6 - Multiple


class KnowledgeType(str, Enum):
    """Knowledge types with passing thresholds."""

    FACTUAL = "factual"          # 70% passing
    CONCEPTUAL = "conceptual"    # 80% passing
    PROCEDURAL = "procedural"    # 85% passing


class FidelityType(str, Enum):
    """Fidelity classification for atom content origin."""

    VERBATIM_EXTRACT = "verbatim_extract"      # Exact quote from source
    REPHRASED_FACT = "rephrased_fact"          # Reworded but factually identical
    AI_SCENARIO_ENRICHMENT = "ai_scenario_enrichment"  # AI-generated scenario/example


@dataclass
class GeneratedAtom:
    """A generated learning atom with full traceability."""

    card_id: str
    atom_type: AtomType
    front: str
    back: str
    knowledge_type: KnowledgeType
    tags: list[str] = field(default_factory=list)
    source_section_id: str = ""
    content_json: dict[str, Any] | None = None  # For MCQ, matching, numeric, etc.
    quality_score: float | None = None
    quality_grade: str | None = None

    # --- FIDELITY TRACKING (Hydration Audit) ---
    is_hydrated: bool = False  # True if scenario NOT in source text
    fidelity_type: str = "verbatim_extract"  # verbatim_extract | rephrased_fact | ai_scenario_enrichment
    source_fact_basis: str | None = None  # The exact raw fact from source used as anchor

    # Database linkage (set by generation pipeline)
    concept_id: str | None = None  # UUID of linked Concept
    module_uuid: str | None = None  # UUID of linked Module record


@dataclass
class GenerationResult:
    """Result of atom generation for a section."""

    section_id: str
    atoms: list[GeneratedAtom]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ============================================================================
# Evidence-Based Prompts
# ============================================================================

SYSTEM_PROMPT = """You are an expert CCNA instructor creating high-quality learning content following evidence-based principles from learning science research.

CRITICAL RULES:

1. ATOMICITY (FSRS Stability Formula)
   - ONE fact per item. Never combine multiple facts.
   - Formula: S_composite = (S_a × S_b) / (S_a + S_b)
   - Two facts with S=30 days each → S_composite=15 days (HALF retention!)
   - If an answer needs "and", "also", or multiple sentences, SPLIT into separate items.

2. *** MANDATORY ANSWER LENGTH - THIS IS CRITICAL ***
   - Questions: 8-15 words optimal, max 25 words
   - ALL ANSWERS MUST BE AT LEAST 10 WORDS - NO EXCEPTIONS!
   - Factual answers: 10-18 words (definition + primary use/purpose/context)
   - Conceptual answers: 15-25 words (explanation with why/how mechanism)
   - NEVER write answers shorter than 10 words - they will be REJECTED
   - ALWAYS explain WHY or HOW - never just give a term or short phrase

   BAD EXAMPLES (will be rejected):
   - "Contacts other servers" (3 words - TOO SHORT)
   - "Troubleshoot name resolution" (3 words - TOO SHORT)
   - "TCP" (1 word - TOO SHORT)

   GOOD EXAMPLES:
   - "Query DNS servers to resolve hostnames to IP addresses and diagnose lookup failures" (13 words)
   - "Provides reliable, ordered delivery of data with error checking and flow control mechanisms" (12 words)
   - "Identifies the network portion and host portion of an IP address using binary masking" (14 words)

3. RETRIEVAL STRENGTH
   - Questions MUST require active recall, not recognition
   - BAD: "What does OSPF stand for?" (recognition)
   - GOOD: "What routing protocol uses Dijkstra's algorithm for shortest path?" (recall)
   - Questions should test understanding, not memorization of acronyms

4. CONCRETE > ABSTRACT
   - Use specific examples, real IP addresses, actual commands
   - BAD: "How do you configure a VLAN?"
   - GOOD: "What command creates VLAN 10 named 'Sales'?"

5. NO HALLUCINATION
   - ONLY use information explicitly stated in the source content
   - If information is not in the source, do NOT include it
   - Do NOT infer or expand beyond what is written

6. CISCO TERMINOLOGY
   - Use precise Cisco terminology as stated in the content
   - Match the exact phrasing from CCNA curriculum
   - Include command modes when relevant (Router#, Router(config)#)

7. FIDELITY RULES (Hydration Audit)
   - If you add ANY scenario details not verbatim in the source sentence, set is_hydrated=true
   - Set fidelity_type: verbatim_extract | rephrased_fact | ai_scenario_enrichment
   - Copy the exact source sentence or phrase into source_fact_basis

OUTPUT FORMAT: Always respond with valid JSON arrays/objects as specified in each prompt."""

# Fidelity rules: if you invent a scenario beyond the exact source sentence,
# set is_hydrated=true, choose fidelity_type, and copy the source sentence into source_fact_basis.


FLASHCARD_PROMPT = """Generate atomic flashcards from this CCNA content.

*** CRITICAL: SCENARIO-BASED HYDRATION REQUIRED ***

FIDELITY CHECK - Before writing each card, ask yourself:
- Is this fact ABSTRACT or CONCRETE?
- If ABSTRACT → HYDRATE into a real-world scenario with specific details
- If CONCRETE → Keep the specific details from the source

HYDRATION EXAMPLES:
  ABSTRACT SOURCE: "Metro Ethernet is a type of Ethernet WAN."
  → HYDRATED QUESTION: "A service provider offers a Layer 2 connection between two branch offices using standard RJ-45 handoffs and Ethernet frames. What WAN technology is being used?"
  → HYDRATED ANSWER: "Metro Ethernet - a WAN service that extends Ethernet from LAN to MAN/WAN, using familiar Ethernet frames and interfaces for simplified connectivity between sites."

  ABSTRACT SOURCE: "OSPF uses Dijkstra's algorithm."
  → HYDRATED QUESTION: "A network engineer needs a link-state routing protocol that calculates the shortest path to every destination. What algorithm does OSPF use?"
  → HYDRATED ANSWER: "Dijkstra's Shortest Path First (SPF) algorithm - builds a complete topology map and calculates the least-cost path to each destination network."

  CONCRETE SOURCE: "Use 'show ip route' to display the routing table."
  → KEEP AS-IS: "What privileged EXEC command displays the routing table on a Cisco router?"
  → ANSWER: "show ip route - displays the routing table including directly connected, static, and dynamically learned routes with their metrics."

REQUIREMENTS:
1. ONE fact per card - if you need "and", make two cards
2. Question: 8-15 words, tests specific knowledge IN A SCENARIO
3. Answer: 10-20 words explaining PURPOSE, FUNCTION, or SIGNIFICANCE
4. Include context clues in question without giving away answer
5. Use exact Cisco terminology from the source
6. TRACK FIDELITY: Set is_hydrated=true if you added scenario details not in source

KNOWLEDGE TYPE GUIDELINES:
- factual: Definition + primary use case or purpose (10-18 words minimum)
- conceptual: How it works + why it matters (15-25 words)
- procedural: Command + what it accomplishes + when to use (10-20 words)

Return JSON array:
[
  {{
    "card_id": "{section_id}-FC-001",
    "front": "scenario-based question testing single fact",
    "back": "answer with at least 10 words explaining purpose and context",
    "tags": ["topic", "subtopic"],
    "knowledge_type": "factual|conceptual|procedural",
    "is_hydrated": true,
    "fidelity_type": "verbatim_extract|rephrased_fact|ai_scenario_enrichment",
    "source_fact_basis": "the exact phrase from source this card is based on"
  }}
]

Generate 5-10 cards. Increment the number suffix for each card (001, 002, 003...).

SECTION ID: {section_id}
CONTENT:
{content}"""


MCQ_PROMPT = """Generate MCQ questions from this CCNA content.

*** CRITICAL: SCENARIO-BASED STEMS REQUIRED ***

HYDRATION RULE: Every MCQ stem MUST present a realistic network scenario.

BAD STEM: "What protocol operates at Layer 3?"
GOOD STEM: "A network administrator needs to route packets between different subnets. Which protocol provides logical addressing and routing decisions at the appropriate OSI layer?"

BAD STEM: "What is the default administrative distance of OSPF?"
GOOD STEM: "A router learns the same destination network via both EIGRP (AD 90) and OSPF. Which route will be installed in the routing table and why?"

REQUIREMENTS:
1. Stem: SCENARIO-BASED question, 15-30 words describing a real situation
2. Correct answer: Unambiguous, precise, 8-15 words
3. Distractors (3): Plausible but clearly wrong to knowledgeable person
   - Common misconceptions from the CCNA exam
   - Related but incorrect terms
   - Partially correct statements
4. 4 options total (research shows diminishing returns beyond 4)
5. AVOID "all of the above" / "none of the above"
6. Each option should be similar length
7. TRACK FIDELITY: Include source_fact_basis

Return JSON array:
[
  {{
    "card_id": "{section_id}-MCQ-001",
    "front": "scenario-based question stem describing a real network situation",
    "correct_answer": "correct option text with explanation",
    "distractors": ["plausible wrong answer 1", "plausible wrong answer 2", "plausible wrong answer 3"],
    "explanation": "brief explanation of why correct answer is right and why distractors are wrong",
    "knowledge_type": "conceptual|procedural",
    "is_hydrated": true,
    "fidelity_type": "ai_scenario_enrichment",
    "source_fact_basis": "the exact fact from source being tested"
  }}
]

Generate 3-5 MCQs. Increment the number suffix for each (001, 002, 003...).

SECTION ID: {section_id}
CONTENT:
{content}"""


CLOZE_PROMPT = """Generate cloze deletion cards for key terminology from this CCNA content.

*** CRITICAL: SCENARIO-CONTEXT CLOZE REQUIRED ***

HYDRATION RULE: Embed the cloze in a realistic scenario sentence, not a bare definition.

BAD CLOZE: "The {{{{c1::OSI model}}}} has seven layers."
GOOD CLOZE: "When troubleshooting a network issue, a technician uses the {{{{c1::OSI model}}}} to systematically isolate problems layer by layer."

BAD CLOZE: "{{{{c1::OSPF}}}} is a link-state routing protocol."
GOOD CLOZE: "A network engineer configures {{{{c1::OSPF}}}} because the enterprise network requires a scalable link-state protocol that converges quickly after topology changes."

REQUIREMENTS:
1. One blank per card (1-2 blanks maximum)
2. SCENARIO CONTEXT: Embed in a realistic networking situation
3. Context must make answer unambiguous to someone who knows the material
4. Blank should be the key term being tested
5. Surrounding text provides retrieval cues AND real-world relevance
6. Use {{{{c1::term}}}} format for blanks

Return JSON array:
[
  {{
    "card_id": "{section_id}-CL-001",
    "front": "In a [realistic scenario], the {{{{c1::term}}}} is used to [accomplish what]...",
    "back": "term",
    "tags": ["topic", "terminology"],
    "knowledge_type": "factual",
    "is_hydrated": true,
    "fidelity_type": "ai_scenario_enrichment",
    "source_fact_basis": "the exact definition or fact from source"
  }}
]

Generate 3-5 cloze cards. Increment the number suffix for each (001, 002, 003...).

SECTION ID: {section_id}
CONTENT:
{content}"""


PARSONS_PROMPT = """Generate Parsons problems from these CLI commands.

REQUIREMENTS:
1. 3-6 steps per problem (cognitive load limit)
2. Each step: Single command or small command group
3. Include mode transitions (enable, config t, interface)
4. Provide clear scenario of what to accomplish
5. Add 1-2 distractor steps (plausible but wrong)

Return JSON array:
[
  {{
    "card_id": "{section_id}-PAR-001",
    "scenario": "Configure [specific task] on [device]",
    "correct_sequence": ["enable", "configure terminal", "interface g0/0", "ip address 192.168.1.1 255.255.255.0", "no shutdown"],
    "distractors": ["wrong step 1", "wrong step 2"],
    "starting_mode": "user EXEC",
    "tags": ["commands", "configuration"]
  }}
]

Generate 1-3 Parsons problems. Increment the number suffix for each (001, 002...).

SECTION ID: {section_id}
COMMANDS AND CONTEXT:
{content}"""


COMPARE_PROMPT = """Generate comparison questions from this CCNA content.

REQUIREMENTS:
1. Compare exactly TWO related concepts
2. Question asks for specific difference or similarity
3. Answer is concise and atomic (one comparison point)
4. Focus on practical/operational differences

Return JSON array:
[
  {{
    "card_id": "{section_id}-CMP-001",
    "front": "What is the key difference between [A] and [B] regarding [specific aspect]?",
    "back": "[A] does X while [B] does Y",
    "concepts": ["concept_a", "concept_b"],
    "comparison_aspect": "what aspect is being compared",
    "tags": ["comparison", "topic"],
    "knowledge_type": "conceptual"
  }}
]

Generate 2-3 comparison cards. Increment the number suffix for each (001, 002...).

SECTION ID: {section_id}
CONTENT:
{content}"""


MATCHING_PROMPT = """Generate matching questions from this CCNA content.

REQUIREMENTS:
1. Maximum 6 pairs (working memory limit)
2. Each pair should be clearly related
3. Left side: Term/concept
4. Right side: Definition/description
5. No duplicate or overlapping matches

Return JSON array:
[
  {{
    "card_id": "{section_id}-MAT-001",
    "front": "Match the following network terms with their descriptions:",
    "pairs": [
      {{"left": "term1", "right": "definition1"}},
      {{"left": "term2", "right": "definition2"}},
      {{"left": "term3", "right": "definition3"}},
      {{"left": "term4", "right": "definition4"}}
    ],
    "tags": ["matching", "topic"],
    "knowledge_type": "factual"
  }}
]

Generate 1-2 matching exercises. Increment the number suffix for each (001, 002).

SECTION ID: {section_id}
CONTENT:
{content}"""


TRUE_FALSE_PROMPT = """Generate true/false questions from this CCNA content.

*** CRITICAL: SCENARIO-BASED STATEMENTS REQUIRED ***

HYDRATION RULE: Frame each statement as something a network professional might encounter or believe.

BAD STATEMENT: "OSPF uses cost as its metric."
GOOD STATEMENT: "A network engineer configuring OSPF on enterprise routers should expect bandwidth to be the primary factor in path selection, since OSPF calculates cost based on interface bandwidth."

BAD STATEMENT: "Switches operate at Layer 2."
GOOD STATEMENT: "When a frame arrives at a Cisco switch, it uses the destination MAC address to make forwarding decisions because switches operate at Layer 2 of the OSI model."

FALSE STATEMENT TECHNIQUE - Use common misconceptions:
GOOD FALSE: "A junior admin believes that configuring a default gateway on a switch is unnecessary since switches don't route packets." (FALSE - management traffic needs it)
GOOD FALSE: "During a security audit, a technician assumes that disabling unused ports automatically enables port security." (FALSE - port security must be explicitly configured)

REQUIREMENTS:
1. SCENARIO CONTEXT: Frame as a real-world situation or belief
2. Statement should be clearly true or false (no ambiguity)
3. Avoid double negatives
4. Test single concept per question
5. Include detailed explanation (why true AND why the opposite would be wrong)
6. For FALSE statements: Use common CCNA exam misconceptions

Return JSON array:
[
  {{
    "card_id": "{section_id}-TF-001",
    "front": "In a [scenario], [statement that is either true or false]",
    "correct": true,
    "explanation": "This is true/false because [detailed reason]. The opposite would be wrong because [why].",
    "tags": ["true_false", "topic"],
    "knowledge_type": "factual|conceptual",
    "is_hydrated": true,
    "fidelity_type": "ai_scenario_enrichment",
    "source_fact_basis": "the exact fact from source being tested"
  }}
]

Generate 3-5 true/false questions. Increment the number suffix for each (001, 002, 003...).

SECTION ID: {section_id}
CONTENT:
{content}"""


# =============================================================================
# NUMERIC PROMPT (Binary/Hex/Subnetting - Critical for Modules 5, 10, 11)
# =============================================================================

NUMERIC_PROMPT = """Generate NUMERIC calculation practice problems from this CCNA content.

This is for EXAM-CRITICAL content: Binary conversions, Hexadecimal, Subnetting calculations.

REQUIREMENTS:
1. Create calculation problems that test:
   - Binary ↔ Decimal conversions
   - Decimal ↔ Hexadecimal conversions
   - Subnet mask calculations
   - Network/Host portion identification
   - Wildcard mask calculations
   - Available hosts per subnet

2. Each problem must have:
   - Clear question with specific values
   - Correct numerical answer
   - Step-by-step solution process
   - Source fact basis (the concept being tested)

3. Vary difficulty:
   - Easy: Single conversion (e.g., 192 to binary)
   - Medium: Multi-step (e.g., find network address)
   - Hard: Full subnet design problems

4. FIDELITY TRACKING:
   - is_hydrated: true (calculations are AI-generated scenarios)
   - fidelity_type: "ai_scenario_enrichment"
   - source_fact_basis: The conceptual rule being applied

Return JSON array:
[
  {{
    "card_id": "{section_id}-NUM-001",
    "front": "Convert the decimal number 192 to binary.",
    "back": "11000000",
    "content_json": {{
      "question": "Convert 192 to binary",
      "answer": "11000000",
      "answer_type": "binary",
      "steps": "128+64=192, so positions 7 and 6 are 1: 11000000",
      "difficulty": 1
    }},
    "tags": ["binary", "conversion", "calculation"],
    "knowledge_type": "procedural",
    "is_hydrated": true,
    "fidelity_type": "ai_scenario_enrichment",
    "source_fact_basis": "Binary positional notation: each bit position represents a power of 2"
  }},
  {{
    "card_id": "{section_id}-NUM-002",
    "front": "Given IP 192.168.10.50/26, what is the network address?",
    "back": "192.168.10.0",
    "content_json": {{
      "question": "Find network address for 192.168.10.50/26",
      "answer": "192.168.10.0",
      "answer_type": "ip_address",
      "steps": "/26 = 255.255.255.192 mask. 50 AND 192 = 0. Network: 192.168.10.0",
      "difficulty": 2
    }},
    "tags": ["subnetting", "network-address", "calculation"],
    "knowledge_type": "procedural",
    "is_hydrated": true,
    "fidelity_type": "ai_scenario_enrichment",
    "source_fact_basis": "Network address is found by ANDing the IP with the subnet mask"
  }}
]

Generate 3-6 numeric problems of varying difficulty. Increment the number suffix (001, 002, 003...).

SECTION ID: {section_id}
CONTENT:
{content}"""


class AtomizerService:
    """
    AI-powered content atomizer using Gemini.

    Generates learning atoms from parsed CCNA content following
    evidence-based quality principles.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize the atomizer service.

        Args:
            api_key: Gemini API key. If None, uses settings.
        """
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = settings.ai_model
        self._client = None

        # Type distribution from config
        self.type_distribution = {
            AtomType.FLASHCARD: settings.ccna_flashcard_percentage,
            AtomType.MCQ: settings.ccna_mcq_percentage,
            AtomType.CLOZE: settings.ccna_cloze_percentage,
            AtomType.PARSONS: settings.ccna_parsons_percentage,
        }

    @property
    def client(self):
        """Lazy-load Gemini client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("Gemini API key not configured")

            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_PROMPT,
            )
        return self._client

    async def atomize_section(
        self,
        section: Section,
        target_types: list[AtomType] | None = None,
    ) -> GenerationResult:
        """
        Generate learning atoms from a section.

        Args:
            section: Parsed section content
            target_types: Specific atom types to generate (or all based on content)

        Returns:
            GenerationResult with atoms, errors, and warnings
        """
        atoms: list[GeneratedAtom] = []
        errors: list[str] = []
        warnings: list[str] = []

        # Determine which types to generate based on content
        if target_types is None:
            target_types = self._determine_types_for_section(section)

        logger.info(
            f"Generating atoms for section {section.id}: {[t.value for t in target_types]}"
        )

        # Generate each type
        for atom_type in target_types:
            try:
                type_atoms = await self._generate_type(section, atom_type)
                atoms.extend(type_atoms)
            except Exception as e:
                error_msg = f"Failed to generate {atom_type.value} for {section.id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return GenerationResult(
            section_id=section.id,
            atoms=atoms,
            errors=errors,
            warnings=warnings,
        )

    def _determine_types_for_section(self, section: Section) -> list[AtomType]:
        """Determine which atom types to generate based on section content."""
        types = [AtomType.FLASHCARD]  # Always generate flashcards
        content_lower = section.raw_content.lower()

        # If section has CLI commands, generate Parsons problems
        if section.all_commands:
            types.append(AtomType.PARSONS)

        # If section has key terms, generate cloze deletions
        if section.all_key_terms:
            types.append(AtomType.CLOZE)

        # If section has tables with comparisons, generate matching
        for table in section.all_tables:
            if table.column_count == 2 and table.row_count >= 3:
                types.append(AtomType.MATCHING)
                break

        # Add MCQ for conceptual content
        if section.density.concept_count >= 2:
            types.append(AtomType.MCQ)

        # --- NUMERIC DETECTION (Binary/Hex/Subnetting) ---
        # Critical for Modules 5, 10, and 11
        numeric_keywords = [
            "binary", "hexadecimal", "hex", "decimal",
            "subnet", "subnetting", "cidr", "/24", "/26", "/28",
            "network address", "broadcast address", "host address",
            "wildcard mask", "255.255.255", "octet",
            "convert", "calculation", "2^", "power of 2",
        ]
        if any(kw in content_lower for kw in numeric_keywords):
            types.append(AtomType.NUMERIC)
            logger.info(f"NUMERIC type enabled for {section.id} (binary/hex/subnet content detected)")

        return types

    async def _generate_type(
        self,
        section: Section,
        atom_type: AtomType,
    ) -> list[GeneratedAtom]:
        """Generate atoms of a specific type for a section."""
        prompt = self._get_prompt_for_type(section, atom_type)
        if not prompt:
            return []

        # Call Gemini
        response = await self._call_gemini(prompt)
        if not response:
            return []

        # Parse response
        atoms = self._parse_response(response, atom_type, section.id)
        return atoms

    def _get_prompt_for_type(
        self,
        section: Section,
        atom_type: AtomType,
    ) -> str | None:
        """Get the appropriate prompt for an atom type."""
        content = section.raw_content

        if atom_type == AtomType.FLASHCARD:
            return FLASHCARD_PROMPT.format(
                section_id=section.id,
                content=content,
            )

        elif atom_type == AtomType.MCQ:
            return MCQ_PROMPT.format(
                section_id=section.id,
                content=content,
            )

        elif atom_type == AtomType.CLOZE:
            # Focus on key terms for cloze
            terms_content = self._format_key_terms(section.all_key_terms, content)
            return CLOZE_PROMPT.format(
                section_id=section.id,
                content=terms_content,
            )

        elif atom_type == AtomType.PARSONS:
            # Focus on commands for Parsons
            if not section.all_commands:
                return None
            commands_content = self._format_commands(section.all_commands, content)
            return PARSONS_PROMPT.format(
                section_id=section.id,
                content=commands_content,
            )

        elif atom_type == AtomType.MATCHING:
            return MATCHING_PROMPT.format(
                section_id=section.id,
                content=content,
            )

        elif atom_type == AtomType.COMPARE:
            return COMPARE_PROMPT.format(
                section_id=section.id,
                content=content,
            )

        elif atom_type == AtomType.TRUE_FALSE:
            return TRUE_FALSE_PROMPT.format(
                section_id=section.id,
                content=content,
            )

        elif atom_type == AtomType.NUMERIC:
            # For binary/hex/subnetting calculations
            return NUMERIC_PROMPT.format(
                section_id=section.id,
                content=content,
            )

        return None

    def _format_key_terms(
        self,
        terms: list[KeyTerm],
        context: str,
    ) -> str:
        """Format key terms for cloze generation."""
        if not terms:
            return context

        terms_text = "KEY TERMS:\n"
        for term in terms:
            terms_text += f"- {term.term}: {term.definition}\n"

        return f"{terms_text}\n\nCONTEXT:\n{context}"

    def _format_commands(
        self,
        commands: list[CLICommand],
        context: str,
    ) -> str:
        """Format CLI commands for Parsons generation."""
        if not commands:
            return context

        cmd_text = "CLI COMMANDS:\n"
        for cmd in commands:
            mode_str = f"[{cmd.mode}]" if cmd.mode != "unknown" else ""
            cmd_text += f"- {mode_str} {cmd.command}\n"

        return f"{cmd_text}\n\nCONTEXT:\n{context}"

    async def _call_gemini(self, prompt: str) -> str | None:
        """Call Gemini API with the given prompt."""
        try:
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,  # Lower for consistency
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
            raise

    def _parse_response(
        self,
        response: str,
        atom_type: AtomType,
        section_id: str,
    ) -> list[GeneratedAtom]:
        """
        Parse Gemini response into GeneratedAtom objects.

        Uses json_repair for robust handling of malformed LLM output:
        - Trailing commas
        - Unescaped quotes in strings
        - Missing brackets
        - Markdown commentary mixed with JSON

        Logs detailed diagnostics on failure to prevent silent data loss.
        """
        atoms = []

        # Extract JSON from response (may be wrapped in markdown code blocks)
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try to find JSON array directly
            json_match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", response)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning(
                    f"Could not find JSON in response for {section_id}. "
                    f"Response preview: {response[:200]}..."
                )
                return atoms

        # Attempt 1: Standard JSON parse
        data = None
        parse_method = "standard"

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"Standard JSON parse failed for {section_id}: {e}")

            # Attempt 2: Use json_repair if available
            if JSON_REPAIR_AVAILABLE and repair_json:
                try:
                    repaired = repair_json(json_str)
                    data = json.loads(repaired)
                    parse_method = "json_repair"
                    logger.info(
                        f"json_repair salvaged response for {section_id} "
                        f"(original error: {e})"
                    )
                except Exception as repair_error:
                    logger.error(
                        f"JSON parse FAILED for {section_id} even after repair. "
                        f"Original error: {e}. Repair error: {repair_error}. "
                        f"JSON preview: {json_str[:300]}..."
                    )
            else:
                # Attempt 3: Manual fixes for common LLM issues
                try:
                    # Remove trailing commas before ] or }
                    fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
                    # Escape unescaped newlines in strings
                    fixed = re.sub(r'(?<!\\)\n(?=[^"]*"[^"]*$)', r'\\n', fixed)
                    data = json.loads(fixed)
                    parse_method = "manual_fix"
                    logger.info(f"Manual JSON fix worked for {section_id}")
                except Exception as fix_error:
                    logger.error(
                        f"JSON parse FAILED for {section_id}. "
                        f"Install json_repair for better LLM output handling: "
                        f"pip install json_repair. "
                        f"Error: {e}. JSON preview: {json_str[:300]}..."
                    )

        if data is None:
            return atoms

        if not isinstance(data, list):
            data = [data]

        # Track conversion stats
        converted = 0
        rejected = 0

        for item in data:
            atom = self._item_to_atom(item, atom_type, section_id)
            if atom:
                atoms.append(atom)
                converted += 1
            else:
                rejected += 1

        logger.debug(
            f"Parsed {section_id}: {converted} atoms converted, "
            f"{rejected} rejected, parse_method={parse_method}"
        )

        return atoms

    def _item_to_atom(
        self,
        item: dict,
        atom_type: AtomType,
        section_id: str,
    ) -> GeneratedAtom | None:
        """Convert a parsed item to a GeneratedAtom."""
        try:
            card_id = item.get("card_id", f"{section_id}-{atom_type.value[:2].upper()}-001")

            # Handle different atom type structures
            if atom_type == AtomType.MCQ:
                front = item.get("front", item.get("stem", ""))
                back = item.get("correct_answer", "")
                content_json = {
                    "options": [back] + item.get("distractors", []),
                    "correct_index": 0,
                    "explanation": item.get("explanation", ""),
                }

            elif atom_type == AtomType.PARSONS:
                front = item.get("scenario", "")
                back = " → ".join(item.get("correct_sequence", []))
                content_json = {
                    "blocks": item.get("correct_sequence", []),
                    "distractors": item.get("distractors", []),
                    "starting_mode": item.get("starting_mode", "user EXEC"),
                }

            elif atom_type == AtomType.MATCHING:
                front = item.get("front", "Match the following:")
                pairs = item.get("pairs", [])
                back = "\n".join([f"{p['left']} → {p['right']}" for p in pairs])
                content_json = {"pairs": pairs}

            elif atom_type == AtomType.TRUE_FALSE:
                front = item.get("front", "")
                back = "True" if item.get("correct", True) else "False"
                content_json = {
                    "correct": item.get("correct", True),
                    "explanation": item.get("explanation", ""),
                }

            elif atom_type == AtomType.COMPARE:
                front = item.get("front", "")
                back = item.get("back", "")
                content_json = {
                    "concepts": item.get("concepts", []),
                    "comparison_aspect": item.get("comparison_aspect", ""),
                }

            elif atom_type == AtomType.NUMERIC:
                # Binary/Hex/Subnetting calculations
                front = item.get("front", "")
                back = item.get("back", "")
                content_json = item.get("content_json", {
                    "question": front,
                    "answer": back,
                    "answer_type": "numeric",
                    "steps": "",
                    "difficulty": 2,
                })

            else:
                # Standard flashcard/cloze
                front = item.get("front", "")
                back = item.get("back", "")
                content_json = None

            # VALIDATION: Reject short flashcard answers (minimum 10 words)
            if atom_type == AtomType.FLASHCARD:
                word_count = len(back.split())
                if word_count < 8:  # Allow some tolerance (8 instead of 10)
                    logger.warning(
                        f"Rejecting short flashcard answer ({word_count} words): "
                        f"'{back[:50]}...' for {section_id}"
                    )
                    return None

            # Determine knowledge type
            kt_str = item.get("knowledge_type", "factual")
            try:
                knowledge_type = KnowledgeType(kt_str)
            except ValueError:
                knowledge_type = KnowledgeType.FACTUAL

            tags = item.get("tags", [])

            # --- FIDELITY TRACKING ---
            # Extract fidelity fields from LLM response (if provided)
            is_hydrated = item.get("is_hydrated", False)
            fidelity_type = item.get("fidelity_type", "verbatim_extract")
            source_fact_basis = item.get("source_fact_basis", None)

            # NUMERIC atoms are always hydrated (AI-generated calculations)
            if atom_type == AtomType.NUMERIC:
                is_hydrated = True
                fidelity_type = "ai_scenario_enrichment"

            return GeneratedAtom(
                card_id=card_id,
                atom_type=atom_type,
                front=front,
                back=back,
                knowledge_type=knowledge_type,
                tags=tags,
                source_section_id=section_id,
                content_json=content_json,
                is_hydrated=is_hydrated,
                fidelity_type=fidelity_type,
                source_fact_basis=source_fact_basis,
            )

        except Exception as e:
            logger.error(f"Error converting item to atom: {e}")
            return None

    async def generate_flashcards(
        self,
        section: Section,
    ) -> list[GeneratedAtom]:
        """Generate flashcards for a section."""
        result = await self.atomize_section(section, [AtomType.FLASHCARD])
        return result.atoms

    async def generate_mcq(
        self,
        section: Section,
    ) -> list[GeneratedAtom]:
        """Generate MCQ questions for a section."""
        result = await self.atomize_section(section, [AtomType.MCQ])
        return result.atoms

    async def generate_cloze(
        self,
        section: Section,
    ) -> list[GeneratedAtom]:
        """Generate cloze deletions for a section."""
        result = await self.atomize_section(section, [AtomType.CLOZE])
        return result.atoms

    async def generate_parsons(
        self,
        section: Section,
    ) -> list[GeneratedAtom]:
        """Generate Parsons problems for a section."""
        result = await self.atomize_section(section, [AtomType.PARSONS])
        return result.atoms

    async def generate_numeric(
        self,
        section: Section,
    ) -> list[GeneratedAtom]:
        """Generate numeric calculation problems (binary/hex/subnetting)."""
        result = await self.atomize_section(section, [AtomType.NUMERIC])
        return result.atoms
