"""
Pedagogy-Informed Transformer.

Applies evidence-backed teaching strategies to atoms.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from ..models import (
    EngagementMode,
    GradingLogic,
    GradingMode,
    KnowledgeDimension,
    RawChunk,
    TransformedAtom,
)
from .base import BaseTransformer, TransformerConfig

logger = logging.getLogger(__name__)


@dataclass
class PedagogyStrategy:
    """Evidence-backed pedagogical strategy."""

    atom_type: str
    grading_mode: GradingMode
    engagement_mode: EngagementMode
    evidence_summary: str
    evidence_id: str | None = None
    confidence: float = 0.0


EVIDENCE_STRATEGY_MAP = {
    ("procedural", "high"): PedagogyStrategy(
        atom_type="parsons",
        grading_mode=GradingMode.ORDER_MATCH,
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        evidence_summary="Scaffolded ordering builds procedural schemas (Parsons & Haden, 2006)",
    ),
    ("procedural", "medium"): PedagogyStrategy(
        atom_type="ordered_list",
        grading_mode=GradingMode.ORDER_MATCH,
        engagement_mode=EngagementMode.ACTIVE,
        evidence_summary="Step sequencing for moderate procedural learning",
    ),
    ("procedural", "low"): PedagogyStrategy(
        atom_type="flashcard",
        grading_mode=GradingMode.FUZZY_MATCH,
        engagement_mode=EngagementMode.ACTIVE,
        evidence_summary="Simple recall effective for basic procedures",
    ),
    ("factual", "high"): PedagogyStrategy(
        atom_type="mcq",
        grading_mode=GradingMode.EXACT_MATCH,
        engagement_mode=EngagementMode.ACTIVE,
        evidence_summary="Discrimination testing enhances factual retention (Roediger & Butler, 2011)",
    ),
    ("factual", "medium"): PedagogyStrategy(
        atom_type="flashcard",
        grading_mode=GradingMode.FUZZY_MATCH,
        engagement_mode=EngagementMode.ACTIVE,
        evidence_summary="Testing effect: retrieval strengthens memory traces (Karpicke & Roediger, 2008)",
    ),
    ("factual", "low"): PedagogyStrategy(
        atom_type="cloze",
        grading_mode=GradingMode.EXACT_MATCH,
        engagement_mode=EngagementMode.ACTIVE,
        evidence_summary="Generation effect for low-complexity facts",
    ),
    ("conceptual", "high"): PedagogyStrategy(
        atom_type="short_answer",
        grading_mode=GradingMode.RUBRIC,
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        evidence_summary="Generation effect: explaining enhances understanding (Chi et al., 1994)",
    ),
    ("conceptual", "medium"): PedagogyStrategy(
        atom_type="explain",
        grading_mode=GradingMode.RUBRIC,
        engagement_mode=EngagementMode.CONSTRUCTIVE,
        evidence_summary="Self-explanation promotes deeper processing",
    ),
    ("conceptual", "low"): PedagogyStrategy(
        atom_type="mcq",
        grading_mode=GradingMode.EXACT_MATCH,
        engagement_mode=EngagementMode.ACTIVE,
        evidence_summary="Discrimination for basic conceptual distinctions",
    ),
    ("metacognitive", "high"): PedagogyStrategy(
        atom_type="scenario",
        grading_mode=GradingMode.RUBRIC,
        engagement_mode=EngagementMode.INTERACTIVE,
        evidence_summary="Authentic contexts develop metacognitive judgment (Bransford et al., 2000)",
    ),
}


@dataclass
class PedagogyTransformerConfig(TransformerConfig):
    """Configuration for pedagogy transformer."""

    use_research_engine: bool = False
    fallback_to_heuristics: bool = True
    include_provenance: bool = True


class PedagogyInformedTransformer(BaseTransformer):
    """Enhances atoms with evidence-backed strategies."""

    name: ClassVar[str] = "pedagogy_informed"
    version: ClassVar[str] = "1.0.0"

    def __init__(self, config: PedagogyTransformerConfig | None = None):
        super().__init__(config or PedagogyTransformerConfig())
        self.config: PedagogyTransformerConfig = self.config

    async def _transform_chunk(self, chunk: RawChunk) -> list[TransformedAtom]:
        """Not used - this is an enhancement transformer."""
        return []

    async def _enhance_atom(self, atom: TransformedAtom) -> TransformedAtom:
        """Enhance atom with evidence-backed strategy."""
        concept_type = self._dimension_to_concept(atom.knowledge_dimension)
        complexity = int(atom.element_interactivity * 5) + 1

        complexity_tier = "high" if complexity >= 4 else "medium" if complexity >= 2 else "low"

        key = (concept_type, complexity_tier)
        strategy = EVIDENCE_STRATEGY_MAP.get(key)

        if strategy:
            if strategy.confidence > 0.5 or not atom.atom_type:
                atom.atom_type = strategy.atom_type
                atom.grading_logic = GradingLogic(mode=strategy.grading_mode)
                atom.engagement_mode = strategy.engagement_mode

            if self.config.include_provenance:
                atom.source_fact_basis = strategy.evidence_summary
                atom.fidelity_type = "heuristic_strategy"
                if strategy.evidence_id:
                    atom.tags.append(f"evidence:{strategy.evidence_id}")

        return atom

    def _dimension_to_concept(self, dimension: KnowledgeDimension) -> str:
        mapping = {
            KnowledgeDimension.FACTUAL: "factual",
            KnowledgeDimension.PROCEDURAL: "procedural",
            KnowledgeDimension.CONCEPTUAL: "conceptual",
            KnowledgeDimension.METACOGNITIVE: "metacognitive",
        }
        return mapping.get(dimension, "factual")
