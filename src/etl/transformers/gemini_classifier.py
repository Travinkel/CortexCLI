"""
Gemini Content Classifier.

Classifies content chunks by type, complexity, and recommended atom templates.
Uses heuristics with optional Gemini API enhancement.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from ..models import (
    AtomContent,
    EngagementMode,
    GradingLogic,
    GradingMode,
    KnowledgeDimension,
    RawChunk,
    TransformedAtom,
)
from .base import BaseTransformer, TransformerConfig

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Analyze this technical content and classify it for learning atom generation.

Content:
{content}

Title: {title}

Classify this content and return JSON:
{{
    "concept_type": "FACTUAL|PROCEDURAL|CONCEPTUAL|METACOGNITIVE",
    "complexity": 1-5,
    "has_cli_commands": true/false,
    "has_code": true/false,
    "recommended_atoms": ["flashcard", "parsons", "mcq", "cloze", "short_answer", "scenario"],
    "key_concepts": ["list", "of", "key", "terms"],
    "reasoning": "Brief explanation of classification"
}}

Classification guide:
- FACTUAL: Definitions, terminology, specific facts (e.g., "What is TCP?")
- PROCEDURAL: Step-by-step processes, configurations, commands (e.g., "Configure OSPF")
- CONCEPTUAL: Explanations of why/how, principles, theories (e.g., "Why does STP exist?")
- METACOGNITIVE: Trade-offs, decisions, troubleshooting strategies

Return ONLY valid JSON, no markdown."""


class ConceptType(str, Enum):
    """Classification of content concept type."""

    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    CONCEPTUAL = "conceptual"
    METACOGNITIVE = "metacognitive"


@dataclass
class ContentClassification:
    """Result of content classification."""

    concept_type: ConceptType
    complexity: int
    has_code: bool
    has_cli_commands: bool
    recommended_atoms: list[str]
    key_concepts: list[str]
    confidence: float = 0.0


@dataclass
class GeminiClassifierConfig(TransformerConfig):
    """Configuration for Gemini classifier."""

    use_gemini: bool = False
    fallback_to_heuristics: bool = True
    model_name: str = "gemini-2.0-flash"
    min_confidence: float = 0.5


class GeminiContentClassifier(BaseTransformer):
    """
    Classifies content chunks for optimal atom generation.

    Classification dimensions:
    - concept_type: FACTUAL, PROCEDURAL, CONCEPTUAL, METACOGNITIVE
    - complexity: 1-5 (cognitive load estimate)
    - recommended_atoms: Suggested atom types

    Uses heuristic classification by default, with optional Gemini enhancement.
    """

    name: ClassVar[str] = "gemini_classifier"
    version: ClassVar[str] = "1.0.0"

    PROCEDURAL_PATTERNS = [
        r"step\s+\d+",
        r"first[,\s]",
        r"then[,\s]",
        r"next[,\s]",
        r"finally[,\s]",
        r"configure\s+",
        r"enable\s+",
        r"create\s+",
        r"set\s+up",
        r"Router[#>]",
        r"Switch[#>]",
        r"(?:show|configure|interface|ip\s+address)",
    ]

    CONCEPTUAL_PATTERNS = [
        r"because\s+",
        r"therefore\s+",
        r"why\s+",
        r"how\s+does",
        r"the\s+reason",
        r"explains?\s+",
        r"concept\s+of",
        r"principle\s+of",
        r"theory\s+of",
    ]

    METACOGNITIVE_PATTERNS = [
        r"choose\s+between",
        r"trade-?off",
        r"when\s+to\s+use",
        r"best\s+practice",
        r"consider\s+",
        r"evaluate\s+",
        r"decide\s+",
        r"troubleshoot",
    ]

    def __init__(self, config: GeminiClassifierConfig | None = None):
        super().__init__(config or GeminiClassifierConfig())
        self.config: GeminiClassifierConfig = self.config
        self._model = None

    def _init_gemini(self):
        """Initialize Gemini model lazily."""
        if self._model is None and self.config.use_gemini:
            try:
                import google.generativeai as genai
                from config import get_settings

                settings = get_settings()
                if settings.gemini_api_key:
                    genai.configure(api_key=settings.gemini_api_key)
                    self._model = genai.GenerativeModel(self.config.model_name)
                    logger.info(f"Gemini model initialized: {self.config.model_name}")
                else:
                    logger.warning("No Gemini API key configured, falling back to heuristics")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
        return self._model

    async def _transform_chunk(self, chunk: RawChunk) -> list[TransformedAtom]:
        """Transform chunk into classified atom."""
        if self.config.use_gemini:
            classification = await self._classify_with_gemini(chunk)
            if classification is None and self.config.fallback_to_heuristics:
                classification = self._classify_heuristic(chunk)
        else:
            classification = self._classify_heuristic(chunk)

        if classification is None:
            return []

        atom = self._create_atom(chunk, classification)

        return [atom]

    async def _classify_with_gemini(self, chunk: RawChunk) -> ContentClassification | None:
        """Classify content using Gemini API."""
        model = self._init_gemini()
        if model is None:
            return None

        try:
            prompt = CLASSIFICATION_PROMPT.format(
                content=chunk.content[:2000],
                title=chunk.title,
            )

            response = model.generate_content(prompt)
            text = response.text.strip()

            if text.startswith("```"):
                text = re.sub(r"```json?\n?", "", text)
                text = re.sub(r"```$", "", text)

            data = json.loads(text)

            concept_type_str = data.get("concept_type", "FACTUAL").upper()
            concept_type = ConceptType(concept_type_str.lower())

            return ContentClassification(
                concept_type=concept_type,
                complexity=int(data.get("complexity", 3)),
                has_code=data.get("has_code", chunk.has_code),
                has_cli_commands=data.get("has_cli_commands", chunk.has_cli_commands),
                recommended_atoms=data.get("recommended_atoms", ["flashcard"]),
                key_concepts=data.get("key_concepts", []),
                confidence=0.9,
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gemini response as JSON: {e}")
            return None
        except Exception as e:
            logger.warning(f"Gemini classification failed: {e}")
            return None

    def _classify_heuristic(self, chunk: RawChunk) -> ContentClassification:
        """Classify content using heuristic patterns."""
        content = chunk.content.lower()
        title = chunk.title.lower()

        procedural_score = sum(
            1 for pattern in self.PROCEDURAL_PATTERNS if re.search(pattern, content, re.IGNORECASE)
        )

        conceptual_score = sum(
            1 for pattern in self.CONCEPTUAL_PATTERNS if re.search(pattern, content, re.IGNORECASE)
        )

        metacognitive_score = sum(
            1 for pattern in self.METACOGNITIVE_PATTERNS if re.search(pattern, content, re.IGNORECASE)
        )

        if chunk.has_cli_commands:
            procedural_score += 3
        if chunk.has_code:
            procedural_score += 2

        scores = {
            ConceptType.PROCEDURAL: procedural_score,
            ConceptType.CONCEPTUAL: conceptual_score,
            ConceptType.METACOGNITIVE: metacognitive_score,
            ConceptType.FACTUAL: 1,
        }

        concept_type = max(scores, key=scores.get)
        max_score = scores[concept_type]

        words = content.split()
        word_count = len(words)
        has_technical_terms = any(
            term in content
            for term in ["protocol", "algorithm", "architecture", "topology", "subnet"]
        )

        complexity = 2
        if word_count > 200:
            complexity += 1
        if has_technical_terms:
            complexity += 1
        if chunk.has_code or chunk.has_cli_commands:
            complexity += 1
        complexity = min(complexity, 5)

        recommended_atoms = self._recommend_atoms(concept_type, complexity, chunk)

        key_concepts = self._extract_key_concepts(content)

        confidence = min(0.7 + (max_score * 0.05), 0.95)

        return ContentClassification(
            concept_type=concept_type,
            complexity=complexity,
            has_code=chunk.has_code,
            has_cli_commands=chunk.has_cli_commands,
            recommended_atoms=recommended_atoms,
            key_concepts=key_concepts,
            confidence=confidence,
        )

    def _recommend_atoms(
        self,
        concept_type: ConceptType,
        complexity: int,
        chunk: RawChunk,
    ) -> list[str]:
        """Recommend atom types based on classification."""
        atoms: list[str] = []

        if concept_type == ConceptType.PROCEDURAL:
            if chunk.has_cli_commands:
                atoms.extend(["parsons", "code_completion"])
            elif complexity >= 3:
                atoms.extend(["parsons", "ordered_list"])
            else:
                atoms.append("ordered_list")

        elif concept_type == ConceptType.CONCEPTUAL:
            if complexity >= 4:
                atoms.extend(["short_answer", "explain"])
            else:
                atoms.extend(["mcq", "flashcard"])

        elif concept_type == ConceptType.METACOGNITIVE:
            atoms.extend(["scenario", "trade_off"])

        else:
            if complexity >= 3:
                atoms.extend(["mcq", "flashcard"])
            else:
                atoms.extend(["flashcard", "cloze"])

        return atoms

    def _extract_key_concepts(self, content: str) -> list[str]:
        """Extract key concepts from content."""
        technical_terms = [
            "ip address",
            "subnet mask",
            "default gateway",
            "router",
            "switch",
            "vlan",
            "ospf",
            "eigrp",
            "bgp",
            "tcp",
            "udp",
            "http",
            "https",
            "dns",
            "dhcp",
            "nat",
            "acl",
            "stp",
            "rstp",
            "etherchannel",
        ]

        found: list[str] = []
        content_lower = content.lower()
        for term in technical_terms:
            if term in content_lower:
                found.append(term)

        return found[:10]

    def _create_atom(
        self,
        chunk: RawChunk,
        classification: ContentClassification,
    ) -> TransformedAtom:
        """Create a TransformedAtom from classified chunk."""
        knowledge_dimension = self._concept_to_dimension(classification.concept_type)

        engagement_mode = EngagementMode.ACTIVE
        if classification.concept_type == ConceptType.CONCEPTUAL:
            engagement_mode = EngagementMode.CONSTRUCTIVE
        elif classification.concept_type == ConceptType.METACOGNITIVE:
            engagement_mode = EngagementMode.INTERACTIVE

        atom_type = classification.recommended_atoms[0] if classification.recommended_atoms else "flashcard"

        grading_mode = GradingMode.FUZZY_MATCH
        if atom_type in ("parsons", "ordered_list"):
            grading_mode = GradingMode.ORDER_MATCH
        elif atom_type == "mcq":
            grading_mode = GradingMode.EXACT_MATCH
        elif atom_type in ("short_answer", "explain", "scenario"):
            grading_mode = GradingMode.RUBRIC

        prompt = chunk.title if chunk.title else "Explain the following concept:"
        answer = chunk.content[:500]

        return TransformedAtom(
            card_id=f"{chunk.source_type}_{chunk.chunk_id}",
            atom_type=atom_type,
            content=AtomContent(
                prompt=prompt,
                answer=answer,
            ),
            grading_logic=GradingLogic(
                mode=grading_mode,
                correct_answer=answer if grading_mode == GradingMode.FUZZY_MATCH else None,
            ),
            engagement_mode=engagement_mode,
            knowledge_dimension=knowledge_dimension,
            element_interactivity=classification.complexity / 5.0,
            source_chunk_id=chunk.chunk_id,
            source_file=chunk.source_file,
            source_type=chunk.source_type,
            quality_score=classification.confidence,
            tags=classification.key_concepts[:5],
            fidelity_type="heuristic_classification",
        )

    def _concept_to_dimension(self, concept_type: ConceptType) -> KnowledgeDimension:
        """Map concept type to knowledge dimension."""
        mapping = {
            ConceptType.FACTUAL: KnowledgeDimension.FACTUAL,
            ConceptType.PROCEDURAL: KnowledgeDimension.PROCEDURAL,
            ConceptType.CONCEPTUAL: KnowledgeDimension.CONCEPTUAL,
            ConceptType.METACOGNITIVE: KnowledgeDimension.METACOGNITIVE,
        }
        return mapping.get(concept_type, KnowledgeDimension.FACTUAL)
