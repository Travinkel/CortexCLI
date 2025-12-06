"""
CCNA Content Generation Module.

Provides evidence-based learning content generation from CCNA module TXT files.
Implements all 15 learning activity types with rigorous quality grading.

Components:
- content_parser: Parse CCNA TXT files into structured content
- atomizer_service: AI-powered content generation using Gemini
- qa_pipeline: Quality assurance and grading (A-F)
- anki_migration: Learning state migration for card replacement
- generation_pipeline: End-to-end orchestration
"""
from __future__ import annotations

from src.ccna.content_parser import (
    CCNAContentParser,
    ModuleContent,
    Section,
    CLICommand,
    KeyTerm,
    Table,
    ContentDensity,
)

from src.ccna.atomizer_service import (
    AtomType,
    KnowledgeType,
    GeneratedAtom,
    GenerationResult,
    AtomizerService,
)

from src.ccna.qa_pipeline import (
    AccuracyResult,
    AtomicityResult,
    LengthResult,
    ClarityResult,
    QAResult,
    QAReport,
    QAPipeline,
)

from src.ccna.anki_migration import (
    CardLearningState,
    CardMatch,
    MigrationResult,
    MigrationReport,
    AnkiMigrationService,
)

from src.ccna.generation_pipeline import (
    GenerationJobResult,
    FullGenerationReport,
    CCNAGenerationPipeline,
)

from src.ccna.concept_generator import (
    GeneratedConcept,
    GeneratedCluster,
    HierarchyResult,
    ConceptGenerator,
    generate_ccna_hierarchy,
)

from src.ccna.curriculum_linker import (
    CurriculumMapping,
    CurriculumLinker,
    setup_ccna_curriculum,
)

__all__ = [
    # Content Parser
    "CCNAContentParser",
    "ModuleContent",
    "Section",
    "CLICommand",
    "KeyTerm",
    "Table",
    "ContentDensity",
    # Atomizer Service
    "AtomType",
    "KnowledgeType",
    "GeneratedAtom",
    "GenerationResult",
    "AtomizerService",
    # QA Pipeline
    "AccuracyResult",
    "AtomicityResult",
    "LengthResult",
    "ClarityResult",
    "QAResult",
    "QAReport",
    "QAPipeline",
    # Anki Migration
    "CardLearningState",
    "CardMatch",
    "MigrationResult",
    "MigrationReport",
    "AnkiMigrationService",
    # Generation Pipeline
    "GenerationJobResult",
    "FullGenerationReport",
    "CCNAGenerationPipeline",
    # Concept Generator
    "GeneratedConcept",
    "GeneratedCluster",
    "HierarchyResult",
    "ConceptGenerator",
    "generate_ccna_hierarchy",
    # Curriculum Linker
    "CurriculumMapping",
    "CurriculumLinker",
    "setup_ccna_curriculum",
]
