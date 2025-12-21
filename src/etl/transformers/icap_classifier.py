"""
ICAP Framework Classifier.

Classifies atoms according to Chi & Wylie's ICAP Framework (2014),
replacing Bloom's Taxonomy with a research-backed engagement model.

ICAP Framework:
- Interactive: Co-creating knowledge with others
- Constructive: Generating new output beyond given material
- Active: Manipulating material without generating new content
- Passive: Receiving information without overt action

Higher engagement modes = better retention and transfer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..models import (
    AtomContent,
    EngagementMode,
    GradingLogic,
    GradingMode,
    KnowledgeDimension,
    TransformedAtom,
)
from .base import BaseTransformer, TransformerConfig

logger = logging.getLogger(__name__)


# =============================================================================
# ICAP Classification Rules
# =============================================================================


@dataclass
class ICAPClassification:
    """Result of ICAP classification."""

    engagement_mode: EngagementMode
    element_interactivity: float  # 0.0-1.0 cognitive load factor
    knowledge_dimension: KnowledgeDimension
    confidence: float  # Confidence in classification


# Atom type -> ICAP mapping
ATOM_TYPE_ICAP_MAP: dict[str, ICAPClassification] = {
    # Passive (receiving information)
    "flashcard": ICAPClassification(
        engagement_mode=EngagementMode.PASSIVE,
        element_interactivity=0.2,
        knowledge_dimension=KnowledgeDimension.FACTUAL,
        confidence=0.9,
    ),
    "reverse_flashcard": ICAPClassification(
        engagement_mode=EngagementMode.PASSIVE,
        element_interactivity=0.3,
        knowledge_dimension=KnowledgeDimension.FACTUAL,
        confidence=0.9,
    ),
    # Active (manipulating without generating)
    "mcq": ICAPClassification(
        engagement_mode=EngagementMode.ACTIVE,
        element_interactivity=0.4,
        knowledge_dimension=KnowledgeDimension.CONCEPTUAL,
        confidence=0.85,
    ),
    "true_false": ICAPClassification(
        engagement_mode=EngagementMode.ACTIVE,
        element_interactivity=0.3,
        knowledge_dimension=KnowledgeDimension.FACTUAL,
        confidence=0.9,
    ),
    "matching": ICAPClassification(
        engagement_mode=EngagementMode.ACTIVE,
        element_interactivity=0.5,
        knowledge_dimension=KnowledgeDimension.CONCEPTUAL,
        confidence=0.85,
    ),
    "cloze": ICAPClassification(
        engagement_mode=EngagementMode.ACTIVE,
        element_interactivity=0.45,
        knowledge_dimension=KnowledgeDimension.FACTUAL,
        confidence=0.85,
    ),
    "cloze_dropdown": ICAPClassification(
        engagement_mode=EngagementMode.ACTIVE,
        element_interactivity=0.35,
        knowledge_dimension=KnowledgeDimension.FACTUAL,
        confidence=0.9,
    ),
    # Constructive (generating new output)
    "parsons": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.7,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.85,
    ),
    "faded_parsons": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.75,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.85,
    ),
    "short_answer": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.6,
        knowledge_dimension=KnowledgeDimension.CONCEPTUAL,
        confidence=0.8,
    ),
    "output_prediction": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.65,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.85,
    ),
    "debugging": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.8,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.85,
    ),
    "bug_identification": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.75,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.85,
    ),
    "numeric": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.55,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.85,
    ),
    "code_submission": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.9,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.9,
    ),
    "sandboxed_code": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.95,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.9,
    ),
    # Interactive (co-creating knowledge)
    "script_concordance_test": ICAPClassification(
        engagement_mode=EngagementMode.INTERACTIVE,
        element_interactivity=0.85,
        knowledge_dimension=KnowledgeDimension.METACOGNITIVE,
        confidence=0.8,
    ),
    "trade_off_analysis": ICAPClassification(
        engagement_mode=EngagementMode.INTERACTIVE,
        element_interactivity=0.9,
        knowledge_dimension=KnowledgeDimension.METACOGNITIVE,
        confidence=0.85,
    ),
    "peer_review": ICAPClassification(
        engagement_mode=EngagementMode.INTERACTIVE,
        element_interactivity=0.95,
        knowledge_dimension=KnowledgeDimension.METACOGNITIVE,
        confidence=0.9,
    ),
    "collaborative_debugging": ICAPClassification(
        engagement_mode=EngagementMode.INTERACTIVE,
        element_interactivity=0.95,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        confidence=0.85,
    ),
    # Metacognitive types
    "confidence_slider": ICAPClassification(
        engagement_mode=EngagementMode.ACTIVE,
        element_interactivity=0.2,
        knowledge_dimension=KnowledgeDimension.METACOGNITIVE,
        confidence=0.95,
    ),
    "effort_rating": ICAPClassification(
        engagement_mode=EngagementMode.ACTIVE,
        element_interactivity=0.2,
        knowledge_dimension=KnowledgeDimension.METACOGNITIVE,
        confidence=0.95,
    ),
    "strategy_selection": ICAPClassification(
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        element_interactivity=0.6,
        knowledge_dimension=KnowledgeDimension.METACOGNITIVE,
        confidence=0.85,
    ),
}


# Content heuristics for classification refinement
CONTENT_HEURISTICS = {
    "generation_indicators": [
        "write",
        "create",
        "design",
        "implement",
        "construct",
        "build",
        "develop",
        "compose",
        "generate",
        "produce",
    ],
    "analysis_indicators": [
        "analyze",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "debug",
        "trace",
        "diagnose",
    ],
    "evaluation_indicators": [
        "evaluate",
        "judge",
        "assess",
        "critique",
        "justify",
        "defend",
        "argue",
        "recommend",
    ],
    "metacognitive_indicators": [
        "reflect",
        "self-assess",
        "confidence",
        "strategy",
        "approach",
        "plan",
        "monitor",
    ],
}


# =============================================================================
# ICAP Classifier Transformer
# =============================================================================


class ICAPClassifier(BaseTransformer):
    """
    Transformer that classifies atoms according to ICAP Framework.

    Replaces Bloom's Taxonomy with Chi & Wylie's (2014) engagement modes:
    - Interactive > Constructive > Active > Passive

    This is an enhancement transformer (atom -> atom).
    """

    name = "icap_classifier"
    version = "1.0.0"

    def __init__(
        self,
        config: TransformerConfig | None = None,
        use_content_heuristics: bool = True,
    ):
        """
        Initialize classifier.

        Args:
            config: Transformer configuration
            use_content_heuristics: Whether to refine classification using content analysis
        """
        super().__init__(config)
        self.use_content_heuristics = use_content_heuristics

    async def _transform_chunk(self, chunk) -> list[TransformedAtom]:
        """Not used - this is an enhancement-only transformer."""
        return []

    async def _enhance_atom(self, atom: TransformedAtom) -> TransformedAtom:
        """
        Classify atom according to ICAP Framework.

        Args:
            atom: Atom to classify

        Returns:
            Atom with ICAP classification applied
        """
        classification = self._classify(atom)

        atom.engagement_mode = classification.engagement_mode
        atom.element_interactivity = classification.element_interactivity
        atom.knowledge_dimension = classification.knowledge_dimension

        # Add classification metadata
        if not hasattr(atom, "icap_confidence"):
            atom.icap_confidence = classification.confidence

        logger.debug(
            f"Classified {atom.card_id} as {classification.engagement_mode.value} "
            f"(confidence: {classification.confidence:.2f})"
        )

        return atom

    def _classify(self, atom: TransformedAtom) -> ICAPClassification:
        """
        Classify atom using type mapping and content heuristics.

        Args:
            atom: Atom to classify

        Returns:
            ICAPClassification
        """
        # Start with type-based classification
        if atom.atom_type in ATOM_TYPE_ICAP_MAP:
            base_classification = ATOM_TYPE_ICAP_MAP[atom.atom_type]
        else:
            # Default for unknown types
            base_classification = ICAPClassification(
                engagement_mode=EngagementMode.ACTIVE,
                element_interactivity=0.5,
                knowledge_dimension=KnowledgeDimension.CONCEPTUAL,
                confidence=0.5,
            )
            logger.warning(
                f"Unknown atom type '{atom.atom_type}', using default classification"
            )

        # Refine with content heuristics if enabled
        if self.use_content_heuristics and atom.content:
            return self._refine_with_content(atom, base_classification)

        return base_classification

    def _refine_with_content(
        self, atom: TransformedAtom, base: ICAPClassification
    ) -> ICAPClassification:
        """
        Refine classification based on content analysis.

        Args:
            atom: Atom being classified
            base: Base classification from type mapping

        Returns:
            Refined classification
        """
        if not atom.content:
            return base

        prompt = atom.content.prompt.lower()

        # Check for generation indicators (upgrade to CONSTRUCTIVE)
        if self._has_indicators(prompt, CONTENT_HEURISTICS["generation_indicators"]):
            if base.engagement_mode == EngagementMode.PASSIVE:
                return ICAPClassification(
                    engagement_mode=EngagementMode.CONSTRUCTIVE,
                    element_interactivity=min(base.element_interactivity + 0.2, 1.0),
                    knowledge_dimension=KnowledgeDimension.PROCEDURAL,
                    confidence=base.confidence * 0.9,  # Slightly lower confidence
                )

        # Check for metacognitive indicators
        if self._has_indicators(prompt, CONTENT_HEURISTICS["metacognitive_indicators"]):
            return ICAPClassification(
                engagement_mode=base.engagement_mode,
                element_interactivity=base.element_interactivity,
                knowledge_dimension=KnowledgeDimension.METACOGNITIVE,
                confidence=base.confidence * 0.95,
            )

        # Check for analysis indicators (upgrade to CONSTRUCTIVE if ACTIVE)
        if self._has_indicators(prompt, CONTENT_HEURISTICS["analysis_indicators"]):
            if base.engagement_mode == EngagementMode.ACTIVE:
                return ICAPClassification(
                    engagement_mode=EngagementMode.CONSTRUCTIVE,
                    element_interactivity=min(base.element_interactivity + 0.15, 1.0),
                    knowledge_dimension=KnowledgeDimension.PROCEDURAL,
                    confidence=base.confidence * 0.9,
                )

        # Check for evaluation indicators (upgrade to INTERACTIVE)
        if self._has_indicators(prompt, CONTENT_HEURISTICS["evaluation_indicators"]):
            if base.engagement_mode in [
                EngagementMode.ACTIVE,
                EngagementMode.CONSTRUCTIVE,
            ]:
                return ICAPClassification(
                    engagement_mode=EngagementMode.INTERACTIVE,
                    element_interactivity=min(base.element_interactivity + 0.25, 1.0),
                    knowledge_dimension=KnowledgeDimension.METACOGNITIVE,
                    confidence=base.confidence * 0.85,
                )

        return base

    def _has_indicators(self, text: str, indicators: list[str]) -> bool:
        """Check if text contains any of the indicators."""
        return any(indicator in text for indicator in indicators)


# =============================================================================
# Element Interactivity Calculator
# =============================================================================


class ElementInteractivityCalculator:
    """
    Calculate element interactivity based on Cognitive Load Theory.

    Element interactivity = number of elements that must be processed
    simultaneously in working memory.

    Factors:
    - Number of concepts referenced
    - Depth of nesting/hierarchy
    - Interdependence of elements
    - Prior knowledge requirements
    """

    def calculate(self, atom: TransformedAtom) -> float:
        """
        Calculate element interactivity for an atom.

        Args:
            atom: Atom to analyze

        Returns:
            Element interactivity score (0.0-1.0)
        """
        if not atom.content:
            return 0.5  # Default

        scores = []

        # Factor 1: Content length (proxy for complexity)
        prompt_length = len(atom.content.prompt)
        length_score = min(prompt_length / 500, 1.0)  # Cap at 500 chars
        scores.append(length_score * 0.3)

        # Factor 2: Code presence (increases interactivity)
        if atom.content.code:
            code_lines = len(atom.content.code.split("\n"))
            code_score = min(code_lines / 15, 1.0)  # Cap at 15 lines
            scores.append(code_score * 0.4)

        # Factor 3: Number of options (for MCQ/matching)
        if atom.content.options:
            option_score = min(len(atom.content.options) / 6, 1.0)  # Cap at 6
            scores.append(option_score * 0.2)

        # Factor 4: Skill count (prerequisite knowledge)
        skill_count = len(atom.skill_codes)
        skill_score = min(skill_count / 3, 1.0)  # Cap at 3 skills
        scores.append(skill_score * 0.1)

        return sum(scores) if scores else 0.5
